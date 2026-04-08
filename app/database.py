from __future__ import annotations

import calendar
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, time, timedelta
from pathlib import Path

from .models import CalendarDayOverride, Employee, HolidayEntry, ManualShiftEntry, OperatorProfile, TimeConstraint, VacationEntry, daily_hours_for_rate, normalize_employee_type, normalize_rate
from .parsers import slugify_name

DB_FILENAME = "ekc_scheduler.db"
logger = logging.getLogger(__name__)

# ============================================================================
# Per-thread connection cache — eliminates open/close churn during burst
# traffic.  Each thread reuses a single SQLite connection.
# ============================================================================

_thread_local = threading.local()


def _make_connection() -> sqlite3.Connection:
    """Create a fresh SQLite connection with tuned PRAGMAs."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=60.0, check_same_thread=False)
    # WAL is persisted to the DB file — survives reconnect.
    # busy_timeout tells SQLite to wait internally before giving up.
    conn.execute("PRAGMA busy_timeout = 120000")  # 120 s
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA wal_autocheckpoint = 1000")
    return conn


def _get_cached_conn() -> sqlite3.Connection:
    """Return a per-thread cached connection, creating or recreating as needed."""
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    conn = _make_connection()
    setattr(_thread_local, "conn", conn)
    return conn


def _get_connection() -> sqlite3.Connection:
    """Return a per-thread cached SQLite connection.

    Reuses the same connection across multiple calls on the same thread,
    which eliminates concurrent-open churn and prevents the
    'unable to open database file' error under burst load.

    Can be used both as a call and as a context manager:
        conn = _get_connection()
        conn.execute(...)     # fine

        with _get_connection() as c:
            c.execute(...)    # commits on exit, returns to cache on normal exit,
                              # rolls back (but keeps conn cached) on exception
    """
    return _ConnWrapper(_get_cached_conn())


class _ConnWrapper:
    """Thin wrapper that lets _get_connection() work as a context manager
    while keeping the connection cached on the thread."""

    def __init__(self, conn: sqlite3.Connection):
        # Use object.__setattr__ to bypass __getattr__ forwarding
        object.__setattr__(self, "_cached_conn", conn)

    def __enter__(self) -> sqlite3.Connection:
        return self._cached_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self._cached_conn.rollback()
            except Exception:
                pass
        # Keep connection cached — just rollback on error
        return False

    def __getattr__(self, name: str):
        return getattr(self._cached_conn, name)

    def __setattr__(self, name, value):
        setattr(self._cached_conn, name, value)

# Текущая версия схемы. Увеличивается при каждом изменении структуры БД.
SCHEMA_VERSION = 3


def get_db_path() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / DB_FILENAME


def init_db() -> None:
    db_path = get_db_path()
    with _get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                employee_id TEXT NOT NULL,
                norm_hours REAL NOT NULL DEFAULT 160.0,
                max_hours REAL NOT NULL DEFAULT 168.0,
                rate REAL NOT NULL DEFAULT 1.0,
                employee_type TEXT NOT NULL DEFAULT 'operator',
                max_consecutive_days INTEGER NOT NULL DEFAULT 5,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS employee_month_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                adjustment REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, year, month)
            );

            CREATE TABLE IF NOT EXISTS vacations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, start_date, end_date)
            );

            CREATE TABLE IF NOT EXISTS study_constraints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                is_strict INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, date, start_time, end_time)
            );

            CREATE TABLE IF NOT EXISTS schedule_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                date TEXT NOT NULL,
                preference_type TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                start_time TEXT,
                end_time TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, date, preference_type)
            );

            CREATE TABLE IF NOT EXISTS monthly_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                preference_type TEXT NOT NULL,
                time_value TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, year, month, preference_type)
            );

            CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holiday_date TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS calendar_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calendar_date TEXT NOT NULL UNIQUE,
                is_non_working INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS manual_shift_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                shift_date TEXT NOT NULL,
                shift_code TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, shift_date, shift_code)
            );

            CREATE TABLE IF NOT EXISTS schedule_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                shift_type TEXT NOT NULL DEFAULT 'operator',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_name, date, start_time, end_time)
            );

            CREATE TABLE IF NOT EXISTS user_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Версионированные миграции — запускаются только один раз
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'schema_version'"
        ).fetchone()
        current_ver = int(row[0]) if row else 0

        if current_ver < 1:
            # --- Migration v1: add start_time/end_time to schedule_preferences ---
            try:
                connection.execute("ALTER TABLE schedule_preferences ADD COLUMN start_time TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                connection.execute("ALTER TABLE schedule_preferences ADD COLUMN end_time TEXT")
            except sqlite3.OperationalError:
                pass

            # --- Добавляем employee_type в operators ---
            operator_columns = {r[1] for r in connection.execute("PRAGMA table_info(operators)").fetchall()}
            if "employee_type" not in operator_columns:
                connection.execute("ALTER TABLE operators ADD COLUMN employee_type TEXT NOT NULL DEFAULT 'operator'")
            connection.execute(
                "UPDATE operators SET employee_type = 'operator' WHERE employee_type IS NULL OR trim(employee_type) = ''"
            )

            connection.execute(
                "INSERT INTO app_settings (key, value) VALUES ('schema_version', '1')"
                " ON CONFLICT(key) DO UPDATE SET value = '1'"
            )
            connection.commit()
            current_ver = 1

        if current_ver < 2:
            # --- Migration v2: перенос hour_adjustment из operators ---
            operator_columns = {r[1] for r in connection.execute("PRAGMA table_info(operators)").fetchall()}
            if "hour_adjustment" in operator_columns:
                rows = connection.execute(
                    "SELECT name, hour_adjustment FROM operators WHERE hour_adjustment != 0"
                ).fetchall()
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS _adjustment_migration (name TEXT PRIMARY KEY, adjustment REAL)
                """)
                for name, adjustment in rows:
                    connection.execute(
                        "INSERT INTO _adjustment_migration (name, adjustment) VALUES (?, ?)",
                        (name, adjustment)
                    )
                connection.execute("""
                    CREATE TABLE operators_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        employee_id TEXT NOT NULL,
                        norm_hours REAL NOT NULL DEFAULT 160.0,
                        max_hours REAL NOT NULL DEFAULT 168.0,
                        rate REAL NOT NULL DEFAULT 1.0,
                        employee_type TEXT NOT NULL DEFAULT 'operator',
                        max_consecutive_days INTEGER NOT NULL DEFAULT 5,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                connection.execute("""
                    INSERT INTO operators_new (id, name, employee_id, norm_hours, max_hours, rate, employee_type, max_consecutive_days, is_active)
                    SELECT id, name, employee_id, norm_hours, max_hours, rate, employee_type, max_consecutive_days, is_active
                    FROM operators
                """)
                connection.execute("DROP TABLE operators")
                connection.execute("ALTER TABLE operators_new RENAME TO operators")

                current_date = date.today()
                migration_rows = connection.execute("SELECT name, adjustment FROM _adjustment_migration").fetchall()
                for name, adjustment in migration_rows:
                    connection.execute(
                        """
                        INSERT INTO employee_month_adjustments (employee_name, year, month, adjustment)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(employee_name, year, month) DO UPDATE SET adjustment = excluded.adjustment
                        """,
                        (name, current_date.year, current_date.month, adjustment),
                    )
                connection.execute("DROP TABLE _adjustment_migration")

            # --- FK migration: добавляем REFERENCES ко всем таблицам с employee_name ---
            _run_fk_migration(connection)

            connection.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('schema_version', '2')"
            )
            connection.commit()
            current_ver = 2

        if current_ver < 3:
            # --- Migration v3: явные индексы для date-range запросов ---
            _run_index_migration(connection)
            connection.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('schema_version', '3')"
            )
            connection.commit()


_FK_TABLES = [
    "vacations",
    "study_constraints",
    "schedule_preferences",
    "monthly_preferences",
    "schedule_assignments",
    "employee_month_adjustments",
    "manual_shift_entries",
    "user_credentials",
]


def _run_fk_migration(conn: sqlite3.Connection) -> None:
    """Пересоздаёт таблицы с REFERENCES operators(name) ON DELETE CASCADE ON UPDATE CASCADE."""
    # Disable FK checks during migration (data may have orphans to clean up)
    conn.execute("PRAGMA foreign_keys = OFF")
    for table_name in _FK_TABLES:
        try:
            info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        except sqlite3.OperationalError:
            continue  # Таблица ещё не существует

        existing_fk = any(row[2] == "operators" for row in conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall())
        if existing_fk:
            continue  # FK уже есть

        # Собираем текущие колонки
        columns = [(row[1], row[2], row[3], row[4], row[5]) for row in info]  # (name, type, notnull, default, pk)
        unique_constraints = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
        # Получаем UNIQUE-колонки из CREATE TABLE — для простоты берём UNIQUE из PRAGMA
        # Определяем уникальный constraint по первому элементу unique из index_list
        unique_cols = None
        for idx in unique_constraints:
            if idx[2]:  # unique=True
                cols = conn.execute(f"PRAGMA index_info({idx[1]})").fetchall()
                if cols and not idx[3].startswith("sqlite_"):
                    unique_cols = [c[2] for c in cols]
                    break

        def _col_def(name: str, ctype: str, notnull: bool, default, pk: bool) -> str:
            # ORDER: name TYPE [NOT NULL] [CONSTRAINTS...]
            # For PK: we want "name INTEGER PRIMARY KEY AUTOINCREMENT"
            if pk:
                return f"{name} INTEGER PRIMARY KEY AUTOINCREMENT"
            parts = [name, ctype]
            if notnull:
                parts.append("NOT NULL")
            if default is not None:
                parts.append(f"DEFAULT {default}")
            if name == "employee_name" and ctype == "TEXT":
                parts.append("REFERENCES operators(name) ON DELETE CASCADE ON UPDATE CASCADE")
            return " ".join(parts)

        col_defs = ", ".join(_col_def(*c) for c in columns)
        if unique_cols:
            col_defs += f", UNIQUE({', '.join(unique_cols)})"

        conn.execute(f"DROP TABLE IF EXISTS {table_name}_fk_new")
        conn.execute(f"CREATE TABLE {table_name}_fk_new ({col_defs})")
        col_names = ", ".join(c[0] for c in columns)
        conn.execute(f"INSERT INTO {table_name}_fk_new ({col_names}) SELECT {col_names} FROM {table_name}")
        conn.execute(f"DROP TABLE {table_name}")
        conn.execute(f"ALTER TABLE {table_name}_fk_new RENAME TO {table_name}")


def _run_index_migration(conn: sqlite3.Connection) -> None:
    """Создаёт индексы для ускорения date-range запросов."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_study_date ON study_constraints(date)",
        "CREATE INDEX IF NOT EXISTS idx_study_employee ON study_constraints(employee_name)",
        "CREATE INDEX IF NOT EXISTS idx_shifts_date ON schedule_assignments(date)",
        "CREATE INDEX IF NOT EXISTS idx_shifts_employee_date ON schedule_assignments(employee_name, date)",
        "CREATE INDEX IF NOT EXISTS idx_prefs_date ON schedule_preferences(date)",
        "CREATE INDEX IF NOT EXISTS idx_prefs_employee_date ON schedule_preferences(employee_name, date)",
        "CREATE INDEX IF NOT EXISTS idx_vacations_employee ON vacations(employee_name)",
        "CREATE INDEX IF NOT EXISTS idx_vacations_dates ON vacations(start_date, end_date)",
        "CREATE INDEX IF NOT EXISTS idx_monthly_employee ON monthly_preferences(employee_name, year, month)",
    ]
    for idx_sql in indexes:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError:
            pass  # Index already exists


# =============================================================================
# Application Settings
# =============================================================================

def get_app_settings(keys: list[str] | tuple[str, ...]) -> dict[str, str]:
    init_db()
    normalized_keys = [key.strip() for key in keys if key and key.strip()]
    if not normalized_keys:
        return {}
    placeholders = ", ".join("?" for _ in normalized_keys)
    with _get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT key, value
            FROM app_settings
            WHERE key IN ({placeholders})
            """,
            tuple(normalized_keys),
        ).fetchall()
    return {str(key): str(value) for key, value in rows}


def set_app_settings(settings: dict[str, str]) -> None:
    init_db()
    normalized_items = {
        key.strip(): (value or "").strip()
        for key, value in settings.items()
        if key and key.strip()
    }
    with _get_connection() as connection:
        for key, value in normalized_items.items():
            if value:
                connection.execute(
                    """
                    INSERT INTO app_settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, value),
                )
            else:
                connection.execute(
                    "DELETE FROM app_settings WHERE key = ?",
                    (key,),
                )
        connection.commit()


# =============================================================================
# Operator Profiles
# =============================================================================

def list_operator_profiles(active_only: bool = False) -> list[OperatorProfile]:
    init_db()
    query = """
        SELECT name, employee_id, norm_hours, max_hours, rate, employee_type, max_consecutive_days, is_active, updated_at
        FROM operators
    """
    params: tuple[object, ...] = ()
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY lower(name)"

    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, params).fetchall()
    return [row_to_profile(row) for row in rows]


def deactivate_operator(name: str) -> None:
    """Sets is_active = 0 for the given operator."""
    init_db()
    with _get_connection() as connection:
        connection.execute(
            "UPDATE operators SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (name,),
        )


def upsert_operator_profile(profile: OperatorProfile, original_name: str | None = None) -> None:
    init_db()
    normalized_rate = normalize_rate(profile.rate)
    daily_hours_for_rate(normalized_rate)
    normalized_employee_type = normalize_employee_type(profile.employee_type)
    with _get_connection() as connection:
        try:
            if original_name and original_name != profile.name:
                updated_operator = connection.execute(
                    """
                    UPDATE operators
                    SET
                        name = ?,
                        employee_id = ?,
                        norm_hours = ?,
                        max_hours = ?,
                        rate = ?,
                        employee_type = ?,
                        max_consecutive_days = ?,
                        is_active = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (
                        profile.name,
                        profile.employee_id or slugify_name(profile.name),
                        profile.norm_hours,
                        profile.max_hours,
                        normalized_rate,
                        normalized_employee_type,
                        profile.max_consecutive_days,
                        1 if profile.is_active else 0,
                        original_name,
                    ),
                )
                if updated_operator.rowcount == 0:
                    raise ValueError("Не удалось найти исходную запись сотрудника для редактирования. Обновите страницу и попробуйте снова.")
                # Обновляем employee_name во ВСЕХ связанных таблицах
                _rename_employee_name(connection, original_name, profile.name)
            else:
                connection.execute(
                    """
                    INSERT INTO operators (name, employee_id, norm_hours, max_hours, rate, employee_type, max_consecutive_days, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        employee_id = excluded.employee_id,
                        norm_hours = excluded.norm_hours,
                        max_hours = excluded.max_hours,
                        rate = excluded.rate,
                        employee_type = excluded.employee_type,
                        max_consecutive_days = excluded.max_consecutive_days,
                        is_active = excluded.is_active,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        profile.name,
                        profile.employee_id or slugify_name(profile.name),
                        profile.norm_hours,
                        profile.max_hours,
                        normalized_rate,
                        normalized_employee_type,
                        profile.max_consecutive_days,
                        1 if profile.is_active else 0,
                    ),
                )
            connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("Не удалось сохранить оператора: сотрудник с таким именем уже есть в базе.") from error


def _rename_employee_name(conn: sqlite3.Connection, old_name: str, new_name: str) -> None:
    """Обновляет имя сотрудника во всех связанных таблицах."""
    for table in ("vacations", "study_constraints", "schedule_preferences",
                  "monthly_preferences", "schedule_assignments", "employee_month_adjustments",
                  "manual_shift_entries", "user_credentials"):
        try:
            conn.execute(
                f"UPDATE {table} SET employee_name = ?, updated_at = CURRENT_TIMESTAMP WHERE employee_name = ?",
                (new_name, old_name),
            )
        except sqlite3.OperationalError:
            pass  # Таблица может не существовать в старых БД


def delete_operator_profile(name: str) -> None:
    init_db()
    with _get_connection() as connection:
        # FK CASCADE удалит связанные записи, но добавляем явное удаление для безопасности
        for table in ("study_constraints", "schedule_preferences", "monthly_preferences",
                       "schedule_assignments", "employee_month_adjustments", "user_credentials",
                       "vacations", "manual_shift_entries"):
            try:
                connection.execute(
                    f"DELETE FROM {table} WHERE employee_name = ?",
                    (name,),
                )
            except sqlite3.OperationalError:
                pass
        connection.execute("DELETE FROM operators WHERE name = ?", (name,))
        connection.commit()


# =============================================================================
# Employee Month Adjustments
# =============================================================================

def get_employee_month_adjustment(name: str, year: int, month: int) -> float:
    """Получает корректировку часов сотрудника для конкретного месяца."""
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT adjustment FROM employee_month_adjustments WHERE employee_name = ? AND year = ? AND month = ?",
            (name, year, month),
        ).fetchone()
        return float(row["adjustment"]) if row else 0.0


def get_employee_month_adjustments_batch(year: int, month: int) -> dict[str, float]:
    """Все корректировки за месяц одним запросом. Возвращает {employee_name: adjustment}."""
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT employee_name, adjustment FROM employee_month_adjustments WHERE year = ? AND month = ?",
            (year, month),
        ).fetchall()
    return {str(r["employee_name"]): float(r["adjustment"]) for r in rows}


def update_employee_month_adjustment(name: str, year: int, month: int, adjustment: float) -> None:
    """Обновляет ручную корректировку часов сотрудника для конкретного месяца."""
    init_db()
    with _get_connection() as connection:
        connection.execute(
            """
            INSERT INTO employee_month_adjustments (employee_name, year, month, adjustment)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(employee_name, year, month) DO UPDATE SET
                adjustment = excluded.adjustment,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, year, month, adjustment),
        )
        connection.commit()


def reset_employee_month_adjustment(name: str, year: int, month: int) -> None:
    """Сбрасывает корректировку часов сотрудника для конкретного месяца в 0."""
    init_db()
    with _get_connection() as connection:
        connection.execute(
            "DELETE FROM employee_month_adjustments WHERE employee_name = ? AND year = ? AND month = ?",
            (name, year, month),
        )
        connection.commit()


# =============================================================================
# Vacation Entries
# =============================================================================

def list_vacation_entries() -> list[VacationEntry]:
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, employee_name, start_date, end_date, note, updated_at FROM vacations ORDER BY start_date, lower(employee_name)"
        ).fetchall()
    return [row_to_vacation(row) for row in rows]


def list_vacation_entries_range(start_date: date, end_date: date) -> list[VacationEntry]:
    """Отпуска, пересекающиеся с диапазоном [start_date, end_date]."""
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, employee_name, start_date, end_date, note, updated_at
            FROM vacations
            WHERE end_date >= ? AND start_date <= ?
            ORDER BY start_date
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    return [row_to_vacation(row) for row in rows]


def upsert_vacation_entry(entry: VacationEntry) -> None:
    init_db()
    with _get_connection() as connection:
        if entry.id and entry.id > 0:
            # Update by ID when editing an existing vacation
            connection.execute(
                """
                UPDATE vacations SET
                    employee_name = ?,
                    start_date = ?,
                    end_date = ?,
                    note = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    entry.employee_name,
                    entry.start_date.isoformat(),
                    entry.end_date.isoformat(),
                    entry.note,
                    entry.id,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO vacations (employee_name, start_date, end_date, note)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(employee_name, start_date, end_date) DO UPDATE SET
                    note = excluded.note,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    entry.employee_name,
                    entry.start_date.isoformat(),
                    entry.end_date.isoformat(),
                    entry.note,
                ),
            )
        connection.commit()


def delete_vacation_entry(entry_id: int) -> None:
    """Удаляет отпуск по ID."""
    init_db()
    with _get_connection() as connection:
        connection.execute("DELETE FROM vacations WHERE id = ?", (entry_id,))
        connection.commit()


def delete_vacation_entry_old(employee_name: str, start_date: date, end_date: date) -> None:
    """Старая версия - удаление по данным."""
    init_db()
    with _get_connection() as connection:
        connection.execute(
            "DELETE FROM vacations WHERE employee_name = ? AND start_date = ? AND end_date = ?",
            (employee_name, start_date.isoformat(), end_date.isoformat()),
        )
        connection.commit()


def list_vacations_for_employee_in_month(employee_name: str, year: int, month: int) -> list[dict]:
    """
    Возвращает список дней отпуска у сотрудника в указанном месяце.
    Каждый элемент - dict с датой и информацией об отпуске.
    """
    vacations = list_vacation_entries()
    vacation_days = []

    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    for entry in vacations:
        if entry.employee_name != employee_name:
            continue

        if entry.end_date < month_start or entry.start_date > month_end:
            continue

        cursor = max(entry.start_date, month_start)
        end_cursor = min(entry.end_date, month_end)

        while cursor <= end_cursor:
            vacation_days.append({
                'date': cursor,
                'start_date': entry.start_date,
                'end_date': entry.end_date,
                'note': entry.note,
            })
            cursor += timedelta(days=1)

    return vacation_days


def get_vacation_days_in_month(employee_name: str, year: int, month: int) -> int:
    """
    Возвращает количество дней отпуска у сотрудника в указанном месяце.
    Считает только рабочие дни (пн-пт), игнорируя выходные.
    """
    from .employee_hydration import _get_vacation_days_for_employee
    all_vacations = list_vacation_entries()
    return _get_vacation_days_for_employee(employee_name, year, month, all_vacations)


# =============================================================================
# Hourly Availability
# =============================================================================

def get_hourly_availability(date_str: str, employee_names: list[str] | None = None) -> dict:
    """
    Возвращает почасовую доступность сотрудников на указанную дату.
    """
    from .models import working_days_in_month

    init_db()  # Защита от вызова без предварительной инициализации

    target_date = date.fromisoformat(date_str)
    year, month = target_date.year, target_date.month
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"

    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row

        if employee_names:
            placeholders = ','.join('?' * len(employee_names))
            study_rows = connection.execute(
                f"""
                SELECT employee_name, date, start_time, end_time, note, is_strict
                FROM study_constraints
                WHERE date BETWEEN ? AND ? AND employee_name IN ({placeholders})
                ORDER BY employee_name, start_time
                """,
                [month_start, month_end] + employee_names
            ).fetchall()
        else:
            study_rows = connection.execute(
                """
                SELECT employee_name, date, start_time, end_time, note, is_strict
                FROM study_constraints
                WHERE date BETWEEN ? AND ?
                ORDER BY employee_name, start_time
                """,
                (month_start, month_end)
            ).fetchall()

        if employee_names:
            pref_rows = connection.execute(
                f"""
                SELECT employee_name, date, preference_type, start_time, end_time, note
                FROM schedule_preferences
                WHERE date BETWEEN ? AND ? AND employee_name IN ({placeholders})
                ORDER BY employee_name, start_time
                """,
                [month_start, month_end] + employee_names
            ).fetchall()
        else:
            pref_rows = connection.execute(
                """
                SELECT employee_name, date, preference_type, start_time, end_time, note
                FROM schedule_preferences
                WHERE date BETWEEN ? AND ?
                ORDER BY employee_name, start_time
                """,
                (month_start, month_end)
            ).fetchall()

        if employee_names:
            shift_rows = connection.execute(
                f"""
                SELECT employee_name, date, start_time, end_time, shift_type, note
                FROM schedule_assignments
                WHERE date BETWEEN ? AND ? AND employee_name IN ({placeholders})
                ORDER BY employee_name, start_time
                """,
                [month_start, month_end] + employee_names
            ).fetchall()
        else:
            shift_rows = connection.execute(
                """
                SELECT employee_name, date, start_time, end_time, shift_type, note
                FROM schedule_assignments
                WHERE date BETWEEN ? AND ?
                ORDER BY employee_name, start_time
                """,
                (month_start, month_end)
            ).fetchall()

        if employee_names:
            vacation_rows = connection.execute(
                f"""
                SELECT employee_name, start_date, end_date, note
                FROM vacations
                WHERE start_date <= ? AND end_date >= ? AND employee_name IN ({placeholders})
                """,
                [month_end, month_start] + employee_names
            ).fetchall()
        else:
            vacation_rows = connection.execute(
                """
                SELECT employee_name, start_date, end_date, note
                FROM vacations
                WHERE start_date <= ? AND end_date >= ?
                """,
                (month_end, month_start)
            ).fetchall()

        if employee_names:
            all_employees = employee_names
        else:
            emp_rows = connection.execute(
                "SELECT name FROM operators WHERE is_active = 1 ORDER BY name"
            ).fetchall()
            all_employees = [row[0] for row in emp_rows]

    def time_in_range(check_time: str, start_time: str, end_time: str) -> bool:
        return start_time <= check_time < end_time

    def date_in_vacation(date_str: str, start_date: str, end_date: str) -> bool:
        return start_date <= date_str <= end_date

    hours = {}
    for hour in range(8, 23):
        hour_str = f"{hour:02d}:00"
        hours[hour_str] = {
            "available": [],
            "blocked": {},
            "preference": {}
        }

    employees_status = {}

    for emp_name in all_employees:
        employees_status[emp_name] = {
            "status": "available",
            "blocked_hours": [],
            "preferences": [],
            "on_vacation": False
        }

        is_on_vacation = False
        for v in vacation_rows:
            if v["employee_name"] == emp_name and date_in_vacation(date_str, v["start_date"], v["end_date"]):
                is_on_vacation = True
                employees_status[emp_name]["on_vacation"] = True
                employees_status[emp_name]["status"] = "vacation"
                employees_status[emp_name]["vacation_note"] = v["note"]
                break

        if is_on_vacation:
            for hour in range(8, 23):
                hour_str = f"{hour:02d}:00"
                hours[hour_str]["blocked"][emp_name] = {
                    "reason": "vacation",
                    "note": next((v["note"] for v in vacation_rows if v["employee_name"] == emp_name), "")
                }
            continue

        for s in study_rows:
            if s["employee_name"] == emp_name and s["date"] == date_str:
                start_h = int(s["start_time"].split(":")[0])
                end_h = int(s["end_time"].split(":")[0])

                for hour in range(max(8, start_h), min(23, end_h)):
                    hour_str = f"{hour:02d}:00"
                    if time_in_range(hour_str, s["start_time"], s["end_time"]):
                        hours[hour_str]["blocked"][emp_name] = {
                            "reason": "study",
                            "start": s["start_time"],
                            "end": s["end_time"],
                            "note": s["note"]
                        }
                        employees_status[emp_name]["blocked_hours"].append({
                            "hour": hour_str,
                            "reason": "study",
                            "note": s["note"]
                        })

        for p in pref_rows:
            if p["employee_name"] == emp_name and p["date"] == date_str:
                if p["preference_type"] == "prefer_off":
                    employees_status[emp_name]["preferences"].append({
                        "type": "prefer_off",
                        "note": p["note"]
                    })
                    for hour in range(8, 23):
                        hour_str = f"{hour:02d}:00"
                        if hour_str not in hours[hour_str]["blocked"].get(emp_name, {}):
                            hours[hour_str]["preference"][emp_name] = {
                                "reason": "prefer_off",
                                "note": p["note"]
                            }
                elif p["preference_type"] == "prefer_time":
                    start_h = int(p["start_time"].split(":")[0]) if p["start_time"] else 0
                    end_h = int(p["end_time"].split(":")[0]) if p["end_time"] else 0

                    for hour in range(max(8, start_h), min(23, end_h)):
                        hour_str = f"{hour:02d}:00"
                        hours[hour_str]["preference"][emp_name] = {
                            "reason": "prefer_time",
                            "start": p["start_time"],
                            "end": p["end_time"],
                            "note": p["note"]
                        }

        for shift in shift_rows:
            if shift["employee_name"] == emp_name and shift["date"] == date_str:
                start_h = int(shift["start_time"].split(":")[0])
                end_h = int(shift["end_time"].split(":")[0])

                for hour in range(max(8, start_h), min(23, end_h)):
                    hour_str = f"{hour:02d}:00"
                    if time_in_range(hour_str, shift["start_time"], shift["end_time"]):
                        hours[hour_str]["blocked"][emp_name] = {
                            "reason": "shift",
                            "start": shift["start_time"],
                            "end": shift["end_time"],
                            "note": shift["note"]
                        }
                        employees_status[emp_name]["blocked_hours"].append({
                            "hour": hour_str,
                            "reason": "shift",
                            "note": shift["note"]
                        })

    for hour_str, hour_data in hours.items():
        for emp_name in all_employees:
            if emp_name not in hour_data["blocked"]:
                if employees_status[emp_name]["on_vacation"]:
                    continue
                hour_data["available"].append(emp_name)

    for emp_name, status in employees_status.items():
        if status["on_vacation"]:
            continue
        if len(status["blocked_hours"]) > 0:
            blocked_hours_count = len(set(b["hour"] for b in status["blocked_hours"]))
            if blocked_hours_count >= 14:
                status["status"] = "blocked"
            else:
                status["status"] = "partial"
        elif len(status["preferences"]) > 0:
            status["status"] = "preference"

    return {
        "date": date_str,
        "hours": hours,
        "employees": employees_status
    }


# =============================================================================
# Holidays, Manual Shifts, Calendar Overrides
# =============================================================================

def list_holiday_entries() -> list[HolidayEntry]:
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT holiday_date, name, updated_at FROM holidays ORDER BY holiday_date"
        ).fetchall()
    return [row_to_holiday(row) for row in rows]


def list_holiday_entries_range(start_date: date, end_date: date) -> list[HolidayEntry]:
    """Праздники в диапазоне дат."""
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT holiday_date, name, updated_at FROM holidays WHERE holiday_date BETWEEN ? AND ? ORDER BY holiday_date",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    return [row_to_holiday(row) for row in rows]


def list_manual_shift_entries() -> list[ManualShiftEntry]:
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT employee_name, shift_date, shift_code, note, updated_at FROM manual_shift_entries ORDER BY shift_date, lower(employee_name), shift_code"
        ).fetchall()
    return [row_to_manual_shift_entry(row) for row in rows]


def upsert_manual_shift_entry(entry: ManualShiftEntry) -> None:
    init_db()
    with _get_connection() as connection:
        connection.execute(
            """
            INSERT INTO manual_shift_entries (employee_name, shift_date, shift_code, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(employee_name, shift_date, shift_code) DO UPDATE SET
                note = excluded.note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entry.employee_name,
                entry.shift_date.isoformat(),
                entry.shift_code,
                entry.note,
            ),
        )
        connection.commit()


def delete_manual_shift_entry(employee_name: str, shift_date: date, shift_code: str) -> None:
    init_db()
    with _get_connection() as connection:
        connection.execute(
            "DELETE FROM manual_shift_entries WHERE employee_name = ? AND shift_date = ? AND shift_code = ?",
            (employee_name, shift_date.isoformat(), shift_code),
        )
        connection.commit()


def upsert_holiday_entry(entry: HolidayEntry) -> None:
    init_db()
    with _get_connection() as connection:
        connection.execute(
            """
            INSERT INTO holidays (holiday_date, name)
            VALUES (?, ?)
            ON CONFLICT(holiday_date) DO UPDATE SET
                name = excluded.name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (entry.holiday_date.isoformat(), entry.name),
        )
        connection.commit()


def delete_holiday_entry(holiday_date: date) -> None:
    init_db()
    with _get_connection() as connection:
        connection.execute("DELETE FROM holidays WHERE holiday_date = ?", (holiday_date.isoformat(),))
        connection.commit()


def list_calendar_day_overrides() -> list[CalendarDayOverride]:
    init_db()
    with _get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT calendar_date, is_non_working, updated_at FROM calendar_overrides ORDER BY calendar_date"
        ).fetchall()
    return [row_to_calendar_override(row) for row in rows]


def replace_calendar_overrides_for_month(
    year: int,
    month: int,
    selected_dates: set[date],
    base_non_working_dates: set[date],
) -> None:
    init_db()
    month_prefix = f"{year:04d}-{month:02d}-%"
    month_dates = {
        date(year, month, day_number)
        for day_number in range(1, monthrange_safe(year, month) + 1)
    }
    with _get_connection() as connection:
        connection.execute("DELETE FROM calendar_overrides WHERE calendar_date LIKE ?", (month_prefix,))
        for target_date in sorted(month_dates):
            selected = target_date in selected_dates
            default_selected = target_date in base_non_working_dates
            if selected == default_selected:
                continue
            connection.execute(
                """
                INSERT INTO calendar_overrides (calendar_date, is_non_working)
                VALUES (?, ?)
                ON CONFLICT(calendar_date) DO UPDATE SET
                    is_non_working = excluded.is_non_working,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (target_date.isoformat(), 1 if selected else 0),
            )
        connection.commit()


# =============================================================================
# Employee Profiles Helpers
# =============================================================================

def ensure_operator_profiles(employees: list[Employee]) -> None:
    if not employees:
        return
    init_db()
    with _get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO operators (name, employee_id, norm_hours, max_hours, rate, employee_type, max_consecutive_days, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(name) DO NOTHING
            """,
            [
                (
                    employee.name,
                    employee.employee_id or slugify_name(employee.name),
                    employee.preferred_hours,
                    employee.max_hours,
                    employee.rate,
                    normalize_employee_type(employee.employee_type),
                    employee.max_consecutive_days,
                )
                for employee in employees
            ],
        )
        connection.commit()


def row_to_profile(row: sqlite3.Row) -> OperatorProfile:
    rate = normalize_rate(float(row["rate"]))
    try:
        employee_type = normalize_employee_type(str(row["employee_type"] or "operator"))
    except ValueError:
        employee_type = "operator"
    return OperatorProfile(
        name=str(row["name"]),
        employee_id=str(row["employee_id"]),
        norm_hours=float(row["norm_hours"]),
        max_hours=float(row["max_hours"]),
        rate=rate,
        employee_type=employee_type,
        max_consecutive_days=int(row["max_consecutive_days"]),
        is_active=bool(row["is_active"]),
        hour_adjustment=0.0,
        updated_at=str(row["updated_at"]),
    )


def row_to_vacation(row: sqlite3.Row) -> VacationEntry:
    return VacationEntry(
        id=int(row["id"]),
        employee_name=str(row["employee_name"]),
        start_date=date.fromisoformat(str(row["start_date"])),
        end_date=date.fromisoformat(str(row["end_date"])),
        note=str(row["note"] or ""),
        updated_at=str(row["updated_at"]),
    )


def row_to_holiday(row: sqlite3.Row) -> HolidayEntry:
    return HolidayEntry(
        holiday_date=date.fromisoformat(str(row["holiday_date"])),
        name=str(row["name"] or ""),
        updated_at=str(row["updated_at"]),
    )


def row_to_manual_shift_entry(row: sqlite3.Row) -> ManualShiftEntry:
    return ManualShiftEntry(
        employee_name=str(row["employee_name"]),
        shift_date=date.fromisoformat(str(row["shift_date"])),
        shift_code=str(row["shift_code"]),
        note=str(row["note"] or ""),
        updated_at=str(row["updated_at"]),
    )


def row_to_calendar_override(row: sqlite3.Row) -> CalendarDayOverride:
    return CalendarDayOverride(
        calendar_date=date.fromisoformat(str(row["calendar_date"])),
        is_non_working=bool(row["is_non_working"]),
        updated_at=str(row["updated_at"]),
    )


def vacations_to_constraints(entries: list[VacationEntry], year: int, month: int) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    for entry in entries:
        cursor = entry.start_date
        while cursor <= entry.end_date:
            if cursor.year == year and cursor.month == month:
                constraints.append(
                    TimeConstraint(
                        employee_name=entry.employee_name,
                        date=cursor,
                        kind="unavailable",
                        start_time=None,
                        end_time=None,
                        strict=True,
                        note=entry.note or f"Отпуск {entry.start_date.isoformat()} - {entry.end_date.isoformat()}",
                    )
                )
            cursor += timedelta(days=1)
    return constraints


def holidays_to_dates(entries: list[HolidayEntry], year: int, month: int) -> set[date]:
    return {entry.holiday_date for entry in entries if entry.holiday_date.year == year and entry.holiday_date.month == month}


def monthrange_safe(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


# =============================================================================
# STUDY CONSTRAINTS (Учёба - строгие ограничения)
# =============================================================================

def upsert_study_constraint(
    employee_name: str,
    date_value: date,
    start_time: str,
    end_time: str,
    note: str = "",
    is_strict: bool = True,
) -> None:
    """Добавляет или обновляет ограничение по учёбе."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO study_constraints (employee_name, date, start_time, end_time, note, is_strict)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_name, date, start_time, end_time) DO UPDATE SET
                note=excluded.note,
                is_strict=excluded.is_strict,
                updated_at=CURRENT_TIMESTAMP
            """,
            (employee_name, date_value.isoformat(), start_time, end_time, note, 1 if is_strict else 0),
        )
        conn.commit()


def delete_study_constraint(
    employee_name: str,
    date_value: date,
    start_time: str,
    end_time: str,
) -> None:
    """Удаляет ограничение по учёбе."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM study_constraints WHERE employee_name=? AND date=? AND start_time=? AND end_time=?",
            (employee_name, date_value.isoformat(), start_time, end_time),
        )
        conn.commit()


def list_study_constraints(year: int, month: int, employee_name: str | None = None) -> list[dict]:
    """Возвращает список ограничений по учёбе."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        if employee_name:
            rows = conn.execute(
                """
                SELECT * FROM study_constraints
                WHERE date >= ? AND date <= ? AND employee_name = ?
                ORDER BY date, start_time
                """,
                (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}", employee_name),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM study_constraints
                WHERE date >= ? AND date <= ?
                ORDER BY employee_name, date, start_time
                """,
                (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "date": date.fromisoformat(row["date"]),
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "note": row["note"],
                "is_strict": bool(row["is_strict"]),
            }
            for row in rows
        ]


def study_constraints_to_time_constraints(study_list: list[dict], year: int, month: int) -> list[TimeConstraint]:
    """Преобразует записи об учёбе в TimeConstraint."""
    constraints = []
    for study in study_list:
        if study["date"].year == year and study["date"].month == month:
            constraints.append(
                TimeConstraint(
                    employee_name=study["employee_name"],
                    date=study["date"],
                    kind="study",
                    start_time=time.fromisoformat(study["start_time"]),
                    end_time=time.fromisoformat(study["end_time"]),
                    strict=study["is_strict"],
                    note=study.get("note", ""),
                )
            )
    return constraints


# =============================================================================
# SCHEDULE PREFERENCES (Пожелания по графику - мягкие ограничения)
# =============================================================================

def upsert_schedule_preference(
    employee_name: str,
    date_value: date,
    preference_type: str,
    note: str = "",
    start_time: str | None = None,
    end_time: str | None = None,
) -> None:
    """Добавляет или обновляет пожелание по графику (выходной)."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO schedule_preferences (employee_name, date, preference_type, note, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_name, date, preference_type) DO UPDATE SET
                note=excluded.note,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                updated_at=CURRENT_TIMESTAMP
            """,
            (employee_name, date_value.isoformat(), preference_type, note, start_time, end_time),
        )
        conn.commit()


def delete_schedule_preference(
    employee_name: str,
    date_value: date,
    preference_type: str,
) -> None:
    """Удаляет пожелание по графику."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM schedule_preferences WHERE employee_name=? AND date=? AND preference_type=?",
            (employee_name, date_value.isoformat(), preference_type),
        )
        conn.commit()


def list_schedule_preferences(year: int, month: int, employee_name: str | None = None) -> list[dict]:
    """Возвращает список пожеланий по графику."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        if employee_name:
            rows = conn.execute(
                """
                SELECT * FROM schedule_preferences
                WHERE date >= ? AND date <= ? AND employee_name = ?
                ORDER BY date
                """,
                (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}", employee_name),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM schedule_preferences
                WHERE date >= ? AND date <= ?
                ORDER BY employee_name, date
                """,
                (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "date": date.fromisoformat(row["date"]),
                "preference_type": row["preference_type"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "note": row["note"],
            }
            for row in rows
        ]


def preferences_to_time_constraints(pref_list: list[dict], year: int, month: int) -> list[TimeConstraint]:
    """Преобразует пожелания в TimeConstraint (нестрогие)."""
    constraints = []
    for pref in pref_list:
        if pref["date"].year == year and pref["date"].month == month:
            constraints.append(
                TimeConstraint(
                    employee_name=pref["employee_name"],
                    date=pref["date"],
                    kind=pref["preference_type"],
                    start_time=None,
                    end_time=None,
                    strict=False,
                    note=pref.get("note", ""),
                )
            )
    return constraints


# =============================================================================
# SCHEDULE ASSIGNMENTS (Назначения смен)
# =============================================================================

def upsert_schedule_assignment(
    employee_name: str,
    date_value: date,
    start_time: str,
    end_time: str,
    shift_type: str = "operator",
    note: str = "",
) -> None:
    """Добавляет или обновляет назначение смены."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO schedule_assignments
            (employee_name, date, start_time, end_time, shift_type, note)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_name, date, start_time, end_time) DO UPDATE SET
                shift_type=excluded.shift_type,
                note=excluded.note,
                updated_at=CURRENT_TIMESTAMP
            """,
            (employee_name, date_value.isoformat(), start_time, end_time, shift_type, note),
        )
        conn.commit()


def delete_schedule_assignment(
    employee_name: str,
    date_value: date,
    start_time: str,
    end_time: str,
) -> None:
    """Удаляет назначение смены."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM schedule_assignments WHERE employee_name=? AND date=? AND start_time=? AND end_time=?",
            (employee_name, date_value.isoformat(), start_time, end_time),
        )
        conn.commit()


def list_schedule_assignments(year: int, month: int, employee_name: str | None = None) -> list[dict]:
    """Возвращает список назначенных смен."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        if employee_name:
            rows = conn.execute(
                """
                SELECT * FROM schedule_assignments
                WHERE date >= ? AND date <= ? AND employee_name = ?
                ORDER BY date, start_time
                """,
                (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}", employee_name),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM schedule_assignments
                WHERE date >= ? AND date <= ?
                ORDER BY employee_name, date, start_time
                """,
                (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "date": date.fromisoformat(row["date"]),
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "shift_type": row["shift_type"],
                "note": row["note"],
            }
            for row in rows
        ]


# =============================================================================
# SCHEDULE ASSIGNMENTS — Range-based queries (для Gantt-редактора v2)
# =============================================================================

def list_schedule_assignments_range(start_date: date, end_date: date) -> list[dict]:
    """Смены в диапазоне дат (включительно)."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM schedule_assignments
            WHERE date >= ? AND date <= ?
            ORDER BY employee_name, date, start_time
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "shift_type": row["shift_type"],
                "note": row["note"],
            }
            for row in rows
        ]


def list_study_constraints_range(start_date: date, end_date: date) -> list[dict]:
    """Ограничения по учёбе в диапазоне дат."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM study_constraints
            WHERE date >= ? AND date <= ?
            ORDER BY employee_name, date, start_time
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "note": row["note"],
                "is_strict": bool(row["is_strict"]),
            }
            for row in rows
        ]


def list_schedule_preferences_range(start_date: date, end_date: date) -> list[dict]:
    """Пожелания по графику в диапазоне дат."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM schedule_preferences
            WHERE date >= ? AND date <= ?
            ORDER BY employee_name, date
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "date": row["date"],
                "preference_type": row["preference_type"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "note": row["note"],
            }
            for row in rows
        ]


# =============================================================================
# Schedule Assignment By-ID Operations (консолидированы в 1 соединение)
# =============================================================================

def find_schedule_assignment_by_id(shift_id: int) -> dict | None:
    """Найти назначение смены по ID."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM schedule_assignments WHERE id = ?",
            (shift_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "employee_name": row["employee_name"],
            "date": row["date"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "shift_type": row["shift_type"],
            "note": row["note"],
        }


def update_schedule_assignment_by_id(
    shift_id: int,
    *,
    employee_name: str | None = None,
    date_value: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    shift_type: str | None = None,
    note: str | None = None,
) -> dict | None:
    """Обновить назначение смены по ID. Возвращает обновлённую строку. 1 соединение."""
    init_db()
    try:
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row
            current = conn.execute(
                "SELECT * FROM schedule_assignments WHERE id = ?",
                (shift_id,),
            ).fetchone()
            if current is None:
                return None

            conn.execute(
                """
                UPDATE schedule_assignments
                SET employee_name=?, date=?, start_time=?, end_time=?,
                    shift_type=?, note=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    employee_name if employee_name is not None else current["employee_name"],
                    date_value if date_value is not None else current["date"],
                    start_time if start_time is not None else current["start_time"],
                    end_time if end_time is not None else current["end_time"],
                    shift_type if shift_type is not None else current["shift_type"],
                    note if note is not None else current["note"],
                    shift_id,
                ),
            )

            updated = conn.execute(
                "SELECT * FROM schedule_assignments WHERE id = ?",
                (shift_id,),
            ).fetchone()
            return {k: updated[k] for k in updated.keys()}
    except sqlite3.IntegrityError as e:
        raise ValueError("Не удалось обновить смену: конфликт с существующей записью.") from e


def delete_schedule_assignment_by_id(shift_id: int) -> bool:
    """Удалить назначение смены по ID. Возвращает True если нашёл."""
    init_db()
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM schedule_assignments WHERE id=?",
                (shift_id,),
            )
            return cursor.rowcount > 0
    except sqlite3.IntegrityError as e:
        raise ValueError("Не удалось удалить смену: нарушение целостности данных.") from e


def create_schedule_assignment_returning(
    employee_name: str,
    date_value: str,
    start_time: str,
    end_time: str,
    shift_type: str = "operator",
    note: str = "",
) -> dict:
    """Создаёт назначение смены и возвращает созданную строку с ID."""
    init_db()
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO schedule_assignments
                (employee_name, date, start_time, end_time, shift_type, note)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(employee_name, date, start_time, end_time) DO UPDATE SET
                    shift_type=excluded.shift_type,
                    note=excluded.note,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (employee_name, date_value, start_time, end_time, shift_type, note),
            )
            new_id = cursor.lastrowid
    except sqlite3.IntegrityError as e:
        raise ValueError("Не удалось создать смену: конфликт с существующей записью.") from e

    return find_schedule_assignment_by_id(new_id) or {
        "id": new_id,
        "employee_name": employee_name,
        "date": date_value,
        "start_time": start_time,
        "end_time": end_time,
        "shift_type": shift_type,
        "note": note,
    }


# =============================================================================
# USER CREDENTIALS (Аутентификация)
# =============================================================================

def create_user_credentials(employee_name: str, password: str, role: str = "employee") -> None:
    """Создает учетные данные пользователя. Пароль хешируется перед сохранением."""
    import os
    salt = os.urandom(16).hex()
    hashed = _hash_password_with_salt(password, salt)
    password_stored = f"{salt}${hashed}"
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO user_credentials (employee_name, password_hash, role, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (employee_name, password_stored, role),
        )


def _hash_password_with_salt(password: str, salt: str) -> str:
    """Хеширует пароль с солью используя SHA-256."""
    import hashlib
    return hashlib.sha256(f"{salt}${password}".encode()).hexdigest()


def _verify_password_hash(password: str, stored_password_hash: str) -> bool:
    """Проверяет пароль против хеша с солью. Формат хранилища: salt$hash."""
    if "$" not in stored_password_hash:
        return password == stored_password_hash
    salt, hash_value = stored_password_hash.split("$", 1)
    return _hash_password_with_salt(password, salt) == hash_value


def get_user_credentials(employee_name: str) -> dict | None:
    """Получает учетные данные пользователя по имени."""
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_credentials WHERE employee_name = ?",
            (employee_name,),
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "password_hash": row["password_hash"],
                "role": row["role"],
            }
        return None


def update_user_password(employee_name: str, new_password: str) -> None:
    """Обновляет пароль пользователя. Пароль хешируется перед сохранением."""
    import os
    salt = os.urandom(16).hex()
    hashed = _hash_password_with_salt(new_password, salt)
    password_stored = f"{salt}${hashed}"
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE user_credentials
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE employee_name = ?
            """,
            (password_stored, employee_name),
        )


def list_all_credentials() -> list[dict]:
    """Получает все учетные данные (для админа)."""
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM user_credentials ORDER BY employee_name").fetchall()

        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "role": row["role"],
            }
            for row in rows
        ]


def init_credentials_for_all_employees(hash_password_func=None) -> list[dict]:
    """Инициализирует учетные данные для всех сотрудников без credentials."""
    from .database import list_operator_profiles

    operators = list_operator_profiles()
    created = []

    for emp in operators:
        existing = get_user_credentials(emp.name)
        if not existing:
            password = generate_password()
            create_user_credentials(emp.name, password, "employee")
            created.append({"employee_name": emp.name, "password": password})

    admin = get_user_credentials("admin")
    if not admin:
        admin_password = generate_password()
        create_user_credentials("admin", admin_password, "admin")
        created.append({"employee_name": "admin", "password": admin_password, "role": "admin"})

    return created


def generate_password() -> str:
    """Генерирует случайный 6-значный пароль."""
    import random
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def hash_password(password: str) -> str:
    """Хеширует пароль с солью. Возвращает salt$hash."""
    import os
    salt = os.urandom(16).hex()
    hashed = _hash_password_with_salt(password, salt)
    return f"{salt}${hashed}"


def verify_password(password: str, stored_password_hash: str) -> bool:
    """Проверяет пароль против хешированного значения. Поддерживает миграцию из plain text."""
    return _verify_password_hash(password, stored_password_hash)


def update_user_role(employee_name: str, new_role: str) -> None:
    """Обновляет роль пользователя (admin/employee)."""
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE user_credentials
            SET role = ?, updated_at = CURRENT_TIMESTAMP
            WHERE employee_name = ?
            """,
            (new_role, employee_name),
        )


def create_user_with_password(employee_name: str, password: str, role: str = "employee") -> bool:
    """Создает нового пользователя с паролем. Пароль хешируется. Возвращает True если успешно."""
    import os
    salt = os.urandom(16).hex()
    hashed = _hash_password_with_salt(password, salt)
    password_stored = f"{salt}${hashed}"
    try:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_credentials (employee_name, password_hash, role, created_at, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (employee_name, password_stored, role),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_with_password(employee_name: str) -> dict | None:
    """Получает пользователя (только для админа). Не возвращает хеш пароля."""
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_credentials WHERE employee_name = ?",
            (employee_name,),
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "role": row["role"],
            }
        return None


def list_all_users_with_passwords() -> list[dict]:
    """Получает всех пользователей (для админа). Не возвращает хеши паролей."""
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM user_credentials ORDER BY employee_name").fetchall()

        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "role": row["role"],
            }
            for row in rows
        ]


def delete_user_credentials(employee_name: str) -> None:
    """Удаляет учетные данные пользователя."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM user_credentials WHERE employee_name = ?", (employee_name,))
        conn.commit()


# =============================================================================
# MONTHLY PREFERENCES (Месячные пожелания)
# =============================================================================

def list_monthly_preferences(year: int, month: int, employee_name: str | None = None) -> list[dict]:
    """Возвращает список месячных пожеланий."""
    init_db()
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        if employee_name:
            rows = conn.execute(
                """
                SELECT * FROM monthly_preferences
                WHERE year = ? AND month = ? AND employee_name = ?
                ORDER BY preference_type
                """,
                (year, month, employee_name),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM monthly_preferences
                WHERE year = ? AND month = ?
                ORDER BY employee_name, preference_type
                """,
                (year, month),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "employee_name": row["employee_name"],
                "year": row["year"],
                "month": row["month"],
                "preference_type": row["preference_type"],
                "time_value": row["time_value"],
                "note": row["note"],
            }
            for row in rows
        ]


def upsert_monthly_preference(
    employee_name: str,
    year: int,
    month: int,
    preference_type: str,
    time_value: str,
    note: str = "",
) -> None:
    """Добавляет или обновляет месячное пожелание."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO monthly_preferences (employee_name, year, month, preference_type, time_value, note)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_name, year, month, preference_type) DO UPDATE SET
                time_value=excluded.time_value,
                note=excluded.note,
                updated_at=CURRENT_TIMESTAMP
            """,
            (employee_name, year, month, preference_type, time_value, note),
        )
        conn.commit()


def delete_monthly_preference(
    employee_name: str,
    year: int,
    month: int,
    preference_type: str,
) -> None:
    """Удаляет месячное пожелание."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM monthly_preferences WHERE employee_name=? AND year=? AND month=? AND preference_type=?",
            (employee_name, year, month, preference_type),
        )
        conn.commit()
